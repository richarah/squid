#!/bin/bash
# Download ACE parser and ERG grammar image
# ACE: http://sweaglesw.org/linguistics/ace/
# ERG: https://github.com/delph-in/erg/releases

set -e

PLATFORM=$(uname -s)
ACE_VERSION="0.9.34"
ERG_VERSION="2024"

echo "=========================================="
echo "SQUID Setup: ACE Parser + ERG Grammar"
echo "=========================================="
echo "Platform: $PLATFORM"
echo ""

# Check if ACE already exists
if [ -f "./ace" ] && [ -x "./ace" ]; then
    echo "✓ ACE parser already exists at ./ace"
    ACE_EXISTS=true
else
    echo "✗ ACE parser not found, will download..."
    ACE_EXISTS=false
fi

# Check if ERG already exists
if [ -f "./erg.dat" ]; then
    echo "✓ ERG grammar already exists at ./erg.dat"
    ERG_EXISTS=true
else
    echo "✗ ERG grammar not found, will download..."
    ERG_EXISTS=false
fi

# If both exist, ask user if they want to re-download
if [ "$ACE_EXISTS" = true ] && [ "$ERG_EXISTS" = true ]; then
    echo ""
    echo "Both ACE and ERG are already installed."
    read -p "Re-download anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping download. Setup complete!"
        exit 0
    fi
fi

echo ""

# Download ACE parser
if [ "$ACE_EXISTS" = false ] || [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading ACE parser version $ACE_VERSION..."
    if [ "$PLATFORM" = "Linux" ]; then
        ACE_URL="http://sweaglesw.org/linguistics/ace/download/ace-${ACE_VERSION}-x86-64.tar.gz"
        if command -v wget &> /dev/null; then
            wget "$ACE_URL" -O ace.tar.gz
        else
            curl -L "$ACE_URL" -o ace.tar.gz
        fi
        tar xzf ace.tar.gz
        chmod +x ace
        rm ace.tar.gz
        echo "✓ ACE parser downloaded successfully"
    elif [ "$PLATFORM" = "Darwin" ]; then
        ACE_URL="http://sweaglesw.org/linguistics/ace/download/ace-${ACE_VERSION}-osx.tar.gz"
        curl -L "$ACE_URL" -o ace.tar.gz
        tar xzf ace.tar.gz
        chmod +x ace
        rm ace.tar.gz
        echo "✓ ACE parser downloaded successfully"
    else
        echo "✗ Unsupported platform: $PLATFORM"
        echo ""
        echo "Please download ACE manually from:"
        echo "  http://sweaglesw.org/linguistics/ace/download/"
        echo ""
        echo "Available downloads:"
        echo "  - Linux (x86-64): ace-${ACE_VERSION}-x86-64.tar.gz"
        echo "  - macOS: ace-${ACE_VERSION}-osx.tar.gz"
        echo "  - Windows: ace-${ACE_VERSION}-x86-64.exe (experimental)"
        exit 1
    fi
fi

# Download ERG grammar image
if [ "$ERG_EXISTS" = false ] || [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading ERG grammar version $ERG_VERSION..."
    # Note: The exact URL may change. Check https://github.com/delph-in/erg/releases
    # for the latest version.
    ERG_URL="http://sweaglesw.org/linguistics/ace/download/erg-${ERG_VERSION}-ubuntu-perplexity.dat"

    if command -v wget &> /dev/null; then
        wget "$ERG_URL" -O erg.dat
    elif command -v curl &> /dev/null; then
        curl -L "$ERG_URL" -o erg.dat
    else
        echo "✗ Error: Neither wget nor curl is available"
        echo "Please install wget or curl and try again"
        exit 1
    fi
    echo "✓ ERG grammar downloaded successfully"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo "ACE binary: ./ace"
echo "ERG grammar: ./erg.dat"
echo ""
echo "Test installation:"
echo "  echo 'The dog barked.' | ./ace -g erg.dat -1"
echo ""
echo "Use with SQUID:"
echo "  python3 -c \"import squid; schema = squid.Schema.from_sqlite('db.db'); print(squid.compile('How many rows?', schema))\""
echo ""
echo "Note: If download URLs are outdated, check:"
echo "  ACE: http://sweaglesw.org/linguistics/ace/download/"
echo "  ERG: https://github.com/delph-in/erg/releases"
echo "=========================================="
