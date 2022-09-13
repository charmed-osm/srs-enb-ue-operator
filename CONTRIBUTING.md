# Contributing to SRS-ENB-UE-Operator

## Build

```bash
snap install charmcraft
charmcraft pack
```

## Deploy

```bash
juju deploy ./srs-enb-ue_ubuntu-20.04-amd64.charm
```

## Develop

Create and activate a virtualenv with the development requirements:

```bash
virtualenv -p python3 venv
source venv/bin/activate
```

Testing is done using `tox`:

```bash
tox -e unit  # Unit tests
tox -e lint  # Linting
tox -e static  # Static analysis
```
