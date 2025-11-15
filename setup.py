from setuptools import setup, find_packages

setup(
    name="survey-exporter",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests>=2.25.0", "urllib3>=1.26.0"],
    entry_points={
        "console_scripts": [
            "survey-gui=survey_exporter.survey_gui:main",
        ],
    },
    author="Kit Choi",
    author_email="kit@kychoi.org",
    description="A tool to export survey responses from Formbricks API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="survey, export, formbricks",
    url="https://github.com/kitchoi/survey-exporter",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.8",
)
