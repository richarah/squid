from setuptools import setup

# Try to compile with mypyc if available
ext_modules = []
try:
    from mypyc.build import mypycify
    ext_modules = mypycify([
        "squid/schema.py",
        "squid/lexicon.py",
        "squid/linker.py",
        "squid/compiler.py",
        "squid/disambiguator.py",
        "squid/rules.py",
    ])
except ImportError:
    pass

setup(ext_modules=ext_modules)
