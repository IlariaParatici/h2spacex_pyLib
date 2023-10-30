from setuptools import find_packages, setup

with open('./README.md', 'r') as readme_file:
    long_description = readme_file.read()

setup(
    name='h2spacex',
    version='0.1.4',
    description='HTTP/2 Single Packet Attack low level library based on Scapy',
    package_dir={"": "h2spacex"},
    packages=find_packages(where="h2spacex"),
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/nxenon/h2spacex',
    author='nxenon',
    author_email='nasiri.aminm@gmail.com',
    license='GPL-3.0',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    install_requires=['scapy==2.4.3'],
    python_requires='>=3.10',
    extras_requires={
        'dev': 'twine==4.0.2'
    },
)
