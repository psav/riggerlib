from setuptools import setup

setup(
    name="riggerlib",
    version='3.0.4',
    description="An event hook framework",
    author="Pete Savage, Sean Myers, Milan Falesnik",
    keywords=["event", "linux", "hook"],
    license="MIT",
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "License :: OSI Approved :: MIT License"],
    packages=['riggerlib'],
    install_requires=['funcsigs', 'flask', 'gunicorn', 'pyzmq', 'requests', 'pyyaml'],
    include_package_data=True,
    url="https://github.com/psav/riggerlib",
)
