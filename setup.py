from setuptools import setup

setup(
    name="riggerlib",
    version='1.0.8',
    description="An event hook framework",
    author="Pete Savage",
    keywords=["event", "linux", "hook"],
    license="PSF",
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "License :: OSI Approved :: Python Software Foundation License"],
    packages=['riggerlib'],
    install_requires=['funcsigs'],
    include_package_data=True,
    url="https://github.com/psav/riggerlib",
)
