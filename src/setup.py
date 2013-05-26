import os
import sys
from setuptools import setup


if sys.argv[-1] == 'test':
    status = os.system("python -m unittest discover -p 'test_*.py'")
    sys.exit(1 if status > 127 else status)


install_requires = [
    'six==1.3.0',
    'tornado==3.0.1',
    'sockjs-tornado==1.0.0',
    'pyzmq==13.1.0',
    'motor==0.1',
    'Momoko==1.0.0',
    'jsonschema==1.2.0',
    'lxml==3.1.0',
]


def long_description():
    return "Light and simple open-source platform for real-time message " \
           "broadcasting in your web applications"


setup(
    name='centrifuge',
    version='0.0.3',
    description="Light and simple open-source platform for real-time message "
                "broadcasting in your web applications",
    long_description=long_description(),
    url='https://github.com/FZambia/centrifuge',
    download_url='https://github.com/FZambia/centrifuge',
    author="Alexandr Emelin",
    author_email='frvzmb@gmail.com',
    license='BSD',
    include_package_data=True,
    packages=['centrifuge', 'centrifuge/web', 'centrifuge/storage'],
    entry_points={
        'console_scripts': [
            'centrifuge = centrifuge.app:main',
            'xpub_xsub = centrifuge.proxy:main'
        ],
    },
    install_requires=install_requires,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Text Processing',
        'Topic :: Utilities'
    ]
)
