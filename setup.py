from setuptools import setup

setup(
  name='logchecker',
  packages=['logchecker'],
  version='0.0.1',
  description='real-time log checker',
  long_description=open('README.md', encoding='utf-8').read(),
  long_description_content_type='text/markdown',
  author='Hans Liu',
  author_email='hansliu.tw@gmail.com',
  url='https://github.com/hansliu/logchecker',
  keywords=['log', 'checker', 'real-time'],
  python_requires='>=3',
  classifiers=[
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
  ],
  entry_points={
    'console_scripts': [
      'logchecker=logchecker:cli',
    ],
  }
)
