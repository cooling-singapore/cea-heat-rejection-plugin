from setuptools import setup, find_packages

__version__ = "1.0.0"

setup(name='cea_heat_rejection_plugin',
      version=__version__,
      description="A Heat Rejection plugin for the City Energy Analyst",
      license='MIT',
      author="Cooling Singapore (Luis Santos, Reynold Mok, Jimeno Fonseca)",
      url='https://github.com/cooling-singapore/cea-heat-rejection-plugin',
      packages=find_packages(),
      package_data={},
      install_requires=[
          'pint',
          'pandas',
          'psychrolib',
          'numpy',
          'matplotlib',
          'geopandas',
      ],
      include_package_data=True)
