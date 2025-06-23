from setuptools import setup, find_packages

setup(
    name="lbo_stack",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "numpy-financial", "pandas", "matplotlib", "typer[all]", "streamlit", "jupyter", "duckdb"
    ],
    entry_points={"console_scripts": ["lbo=lbo_stack.cli:app"]},
)
