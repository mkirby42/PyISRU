from setuptools import setup, find_packages

setup(
    name="py_isru",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "scipy",
        "pandas",
        "dash",
        "plotly",
        "gunicorn",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "pytest-xdist",
            "pytest-timeout",
            "black",
            "mypy",
            "pylint",
            "flake8",
        ],
    },
    python_requires=">=3.8",
) 