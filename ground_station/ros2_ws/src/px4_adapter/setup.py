from setuptools import find_packages, setup

package_name = "px4_adapter"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="UAV Research Team",
    maintainer_email="research@example.com",
    description="Read-only PX4 telemetry adapter",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "px4_telemetry_adapter = px4_adapter.telemetry_node:main",
        ],
    },
)
