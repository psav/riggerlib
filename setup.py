from setuptools import setup

setup(
    name="riggerlib",
    version='2.0.2',
    description="An event hook framework",
    author="Pete Savage, Sean Myers",
    keywords=["event", "linux", "hook"],
    license="MIT",
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "License :: OSI Approved :: MIT License"],
    packages=['riggerlib'],
    install_requires=['funcsigs', 'flask', 'gunicorn', 'pyzmq'],
    include_package_data=True,
    url="https://github.com/psav/riggerlib",
)
