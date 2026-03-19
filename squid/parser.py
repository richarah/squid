"""
ACE parser wrapper with persistent process support.

Wraps the ACE parser (http://sweaglesw.org/linguistics/ace/) and provides
conversion from MRS to DMRS using PyDelphin.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from delphin import dmrs, mrs
from delphin.codecs import simplemrs


class SquidParseError(Exception):
    """Raised when parsing fails."""
    pass


class ERGParser:
    """
    ACE parser wrapper with persistent process support.

    The parser can run in two modes:
    1. One-shot: spawn ACE for each parse call (default)
    2. Persistent: keep ACE running and send sentences via stdin (recommended)

    Use as context manager for persistent mode:
        with ERGParser(...) as parser:
            results = parser.parse("How many singers?")
    """

    def __init__(
        self,
        grm_path: str = "erg.dat",
        ace_path: str = "ace",
        extra_lexicon: Optional[str] = None,
        n_parses: int = 5,
        max_chart_megabytes: int = 1024,
        max_unpack_megabytes: int = 1536,
        max_edges: int = 50000,
        timeout: float = 30.0,
    ):
        """
        Initialize ACE parser wrapper.

        Args:
            grm_path: Path to compiled ERG grammar image (erg.dat)
            ace_path: Path to ACE binary
            extra_lexicon: Path to supplementary TDL lexicon file
            n_parses: Number of best parses to return (1-10)
            max_chart_megabytes: Max memory for chart (MB)
            max_unpack_megabytes: Max memory for unpacking (MB)
            max_edges: Max chart edges
            timeout: Timeout per sentence (seconds)
        """
        self.grm_path = Path(grm_path)
        self.ace_path = Path(ace_path)
        self.extra_lexicon = Path(extra_lexicon) if extra_lexicon else None
        self.n_parses = n_parses
        self.max_chart_megabytes = max_chart_megabytes
        self.max_unpack_megabytes = max_unpack_megabytes
        self.max_edges = max_edges
        self.timeout = timeout

        self._process: Optional[subprocess.Popen] = None

        # Validate paths
        if not self.ace_path.exists():
            raise FileNotFoundError(
                f"ACE binary not found: {self.ace_path}\n\n"
                f"⚠️  ACE parser is NOT included in the SQUID pip package.\n"
                f"It is an external C binary that must be downloaded separately.\n\n"
                f"To install ACE and ERG automatically:\n"
                f"  bash scripts/setup_erg.sh\n\n"
                f"Or download manually from:\n"
                f"  http://sweaglesw.org/linguistics/ace/download/\n"
                f"  (Choose ace-0.9.34-x86-64.tar.gz for Linux or ace-0.9.34-osx.tar.gz for macOS)\n\n"
                f"Extract the binary and ensure it's accessible at: {self.ace_path}"
            )
        if not self.grm_path.exists():
            raise FileNotFoundError(
                f"ERG grammar not found: {self.grm_path}\n\n"
                f"⚠️  ERG (English Resource Grammar) is NOT included in the SQUID pip package.\n"
                f"It is a large compiled grammar image that must be downloaded separately.\n\n"
                f"To install ERG and ACE automatically:\n"
                f"  bash scripts/setup_erg.sh\n\n"
                f"Or download manually from:\n"
                f"  http://sweaglesw.org/linguistics/ace/download/erg-2024-ubuntu-perplexity.dat\n"
                f"  (Or check https://github.com/delph-in/erg/releases for latest version)\n\n"
                f"Save the .dat file to: {self.grm_path}"
            )
        if self.extra_lexicon and not self.extra_lexicon.exists():
            raise FileNotFoundError(
                f"Extra lexicon file not found: {self.extra_lexicon}\n\n"
                f"The extra_lexicon parameter points to a file that doesn't exist.\n"
                f"Please verify the path or remove the extra_lexicon parameter."
            )

    def _build_command(self) -> List[str]:
        """Build the ACE command with all options."""
        cmd = [
            str(self.ace_path),
            "-g", str(self.grm_path),
            "-n", str(self.n_parses),
            "--udx",  # Enable unknown word handling
        ]

        # Add memory limits
        if self.max_chart_megabytes:
            cmd.extend(["--max-chart-megabytes", str(self.max_chart_megabytes)])
        if self.max_unpack_megabytes:
            cmd.extend(["--max-unpack-megabytes", str(self.max_unpack_megabytes)])

        # Add max edges
        if self.max_edges:
            cmd.extend(["--max-words", str(self.max_edges)])

        # Add extra lexicon
        if self.extra_lexicon:
            cmd.extend(["--extra-lexicon", str(self.extra_lexicon)])

        return cmd

    def start(self) -> None:
        """Start the persistent ACE process. Call once."""
        if self._process is not None:
            raise RuntimeError("Parser already started")

        cmd = self._build_command()

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start ACE process: {e}")

    def stop(self) -> None:
        """Shut down the ACE process."""
        if self._process:
            try:
                self._process.stdin.close()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            finally:
                self._process = None

    def __enter__(self) -> ERGParser:
        """Context manager entry: start persistent process."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit: stop persistent process."""
        self.stop()

    def parse(self, sentence: str) -> List[mrs.Mrs]:
        """
        Parse a sentence and return N-best MRS results.

        Args:
            sentence: Input sentence

        Returns:
            List of MRS objects

        Raises:
            SquidParseError: If parsing fails
        """
        if self._process is not None:
            # Use persistent process
            return self._parse_persistent(sentence)
        else:
            # One-shot mode
            return self._parse_oneshot(sentence)

    def _parse_persistent(self, sentence: str) -> List[mrs.Mrs]:
        """Parse using persistent ACE process."""
        if not self._process:
            raise RuntimeError("Parser not started")

        try:
            # Send sentence
            self._process.stdin.write(sentence.strip() + "\n")
            self._process.stdin.flush()

            # Read output until blank line (ACE's delimiter)
            output_lines: List[str] = []
            while True:
                line = self._process.stdout.readline()
                if not line or line.strip() == "":
                    break
                output_lines.append(line)

            output = ''.join(output_lines)

            # Parse MRS from output
            return self._extract_mrs(output)

        except Exception as e:
            raise SquidParseError(f"Persistent parsing failed: {e}")

    def _parse_oneshot(self, sentence: str) -> List[mrs.Mrs]:
        """Parse using one-shot ACE invocation."""
        cmd = self._build_command()

        try:
            result = subprocess.run(
                cmd,
                input=sentence.strip() + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                raise SquidParseError(f"ACE failed: {result.stderr}")

            return self._extract_mrs(result.stdout)

        except subprocess.TimeoutExpired:
            raise SquidParseError(f"Parsing timed out after {self.timeout}s")
        except Exception as e:
            raise SquidParseError(f"One-shot parsing failed: {e}")

    def _extract_mrs(self, ace_output: str) -> List[mrs.Mrs]:
        """
        Extract MRS objects from ACE output.

        Args:
            ace_output: Raw ACE stdout

        Returns:
            List of MRS objects
        """
        mrs_list: List[mrs.Mrs] = []

        # ACE outputs MRS in simplemrs format
        # Each MRS is delimited by blank lines
        try:
            # Split output into individual MRS blocks
            blocks = ace_output.strip().split('\n\n')

            for block in blocks:
                if not block.strip():
                    continue

                # Try to parse as simplemrs
                try:
                    # simplemrs.decode expects a string with the MRS
                    m = simplemrs.decode(block)
                    mrs_list.append(m)
                except Exception:
                    # Skip invalid blocks
                    continue

            return mrs_list

        except Exception as e:
            raise SquidParseError(f"Failed to extract MRS from ACE output: {e}")

    def parse_to_dmrs(self, sentence: str) -> List[dmrs.Dmrs]:
        """
        Parse a sentence and convert to DMRS.

        Args:
            sentence: Input sentence

        Returns:
            List of DMRS objects

        Raises:
            SquidParseError: If parsing fails
        """
        mrs_list = self.parse(sentence)

        dmrs_list: List[dmrs.Dmrs] = []
        for m in mrs_list:
            try:
                # Convert MRS to DMRS (lossless conversion)
                d = dmrs.from_mrs(m)
                dmrs_list.append(d)
            except Exception as e:
                # Skip MRS that can't be converted
                continue

        if not dmrs_list:
            raise SquidParseError(f"No valid DMRS parses for: {sentence!r}")

        return dmrs_list

    def parse_batch(self, sentences: List[str]) -> List[List[mrs.Mrs]]:
        """
        Parse many sentences through one persistent process.

        Args:
            sentences: List of sentences to parse

        Returns:
            List of MRS lists (one per sentence)
        """
        if self._process is None:
            raise RuntimeError(
                "Batch parsing requires persistent mode. "
                "Use `with ERGParser(...) as p:` or call .start()"
            )

        results: List[List[mrs.Mrs]] = []
        for sentence in sentences:
            try:
                mrs_list = self._parse_persistent(sentence)
                results.append(mrs_list)
            except SquidParseError:
                # Return empty list for failed parses
                results.append([])

        return results


# Module-level persistent parser for convenience
_default_parser: Optional[ERGParser] = None


def get_parser(
    grm_path: str = "erg.dat",
    ace_path: str = "ace",
    extra_lexicon: Optional[str] = None,
    n_parses: int = 5,
    max_chart_megabytes: int = 1024,
    max_unpack_megabytes: int = 1536,
    max_edges: int = 50000,
    timeout: float = 30.0,
) -> ERGParser:
    """
    Get or create a module-level persistent parser.

    This is convenient for repeated parsing without managing the process lifecycle.
    The parser will be kept alive for the duration of the Python process.

    Args:
        Same as ERGParser.__init__

    Returns:
        Persistent ERGParser instance
    """
    global _default_parser

    if _default_parser is None:
        _default_parser = ERGParser(
            grm_path=grm_path,
            ace_path=ace_path,
            extra_lexicon=extra_lexicon,
            n_parses=n_parses,
            max_chart_megabytes=max_chart_megabytes,
            max_unpack_megabytes=max_unpack_megabytes,
            max_edges=max_edges,
            timeout=timeout,
        )
        _default_parser.start()

    return _default_parser
