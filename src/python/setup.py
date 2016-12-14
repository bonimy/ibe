import sys
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='ibe',
    version='0.1',
    description='',
    author='',
    author_email='',
    url='',
    install_requires=["funcsigs==1.0.0",
                      "Pylons==0.9.7",
                      "webob==1.0.8",
                      "webtest==1.2",
                      "LEPL==5.1.3",
                     ],
    setup_requires=["PasteScript>=1.6.3"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    package_data={},
    zip_safe=False,
    paster_plugins=['PasteScript', 'Pylons'],
    entry_points="""
    [paste.app_factory]
    main = ibe.config.middleware:make_app

    [paste.app_install]
    main = pylons.util:PylonsInstaller
    """,
)
