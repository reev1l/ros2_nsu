from glob import glob

from setuptools import find_packages, setup

setup(
    name='course_bringup', version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/course_bringup']),
        ('share/course_bringup', ['package.xml']),
        ('share/course_bringup/launch', glob('launch/*.launch.py')),
        ('share/course_bringup/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='reev1l', maintainer_email='reev1l@users.noreply.github.com',
    description='Namespaced patrol launch and pose QoS experiment for PR05.',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={'console_scripts': [
        'pose_relay = course_bringup.pose_relay:main',
        'pose_subscriber = course_bringup.pose_subscriber:main',
    ]},
)
