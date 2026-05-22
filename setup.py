from setuptools import find_packages, setup

package_name = "turtle_draw"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Aluno",
    maintainer_email="aluno@example.com",
    description="Desenha o contorno de uma imagem usando turtlesim.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "desenha_tartaruga = turtle_draw.desenha_tartaruga_node:main",
            "processa_imagem = turtle_draw.processamento_imagem:main",
        ],
    },
)
