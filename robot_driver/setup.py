from setuptools import setup, find_packages

package_name = 'robot_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='you',
    maintainer_email='you@example.com',
    description='Pico robot driver node',
    license='MIT',
    entry_points={
        'console_scripts': [
            'robot_node = robot_driver.robot_node:main',
        ],
    },
)
