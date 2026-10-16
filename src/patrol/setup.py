from setuptools import find_packages, setup

setup(
    name='patrol', version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/patrol']),
        ('share/patrol', ['package.xml']),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='reev1l', maintainer_email='reev1l@users.noreply.github.com',
    description='Pose subscription and timer-driven Twist publisher with runtime parameters for PR03/PR04.',
    license='Apache-2.0',
    entry_points={'console_scripts': ['patrol = patrol.patrol:main']},
)
