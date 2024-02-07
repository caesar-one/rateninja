import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="rateninja",
    version='1.0.2',
    author="Cesare Campagnano",
    description="An asynchronous rate limiter for Python, that automatically handles rate limits and retries. Useful for APIs having strict rate limits.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/caesar-one/rateninja",
    packages=["rateninja"],
    author_email="cesare.campagnano@gmail.com",
    license="Apache License 2.0",
    install_requires=["tqdm"],
)
