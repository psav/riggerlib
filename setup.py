from setuptools import setup

setup(
    name="riggerlib",
    use_scm_version=True,
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
    install_requires=[
        'funcsigs',
        'pyzmq',
        'pyyaml',
        'six',
    ],
    setup_requires=['setuptools_scm'],
    include_package_data=True,
    url="https://github.com/psav/riggerlib",
)
