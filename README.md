# SRS-ENB-UE-Operator

Open-source 4G EnodeB and User emulators developed by [Software Radio Systems (SRS)](https://www.srslte.com/).

## Installation and configuration

```bash
juju deploy charmed-osm-srs-enb-ue --channel edge
```

The easiest method is to configure and deploy at the same time. For it create a YAML configuration file:

```yaml
---
srs-enb-ue:
  bind-address-subnet: <ipv4 address>
  enb-name: <enb name>
  enb-mcc: <mcc>
  enb-mnc: <mnc default>
  enb-rf-device-name: <zmq>
  enb-rf-device-args: <RF Device Name.>
  ue-usim-algo: <The authentication algorithm to use (MILENAGE or XOR).>
  ue-nas-apn: <NAS Access Point Name (APN).>
  ue-device-name: <UE Device Name.>
  ue-device-args: <UE Device arguments.>
```

And run the deploy command:

```bash
juju deploy charmed-osm-srs-enb-ue --config <yaml config file>
```

If you don't wish to configure on deployment, you can install and configure later.

For deploying run the following command:

```bash
juju deploy charmed-osm-srs-enb-ue
```

And configure each parameter with:

```bash
juju config srs-enb-ue bind-address-subnet=<ipv4 address>
```

## Actions

### Attach UE

For attaching the UE to the core network run:

```bash
juju run-action <unit> attach-ue usim-imsi=<IMSI> usim-k=<K> usim-opc=<OPC> --wait
```

### Detach UE

For detaching the UE from the core run:

```bash
juju run-action <unit> detach-ue --wait
```

### Remove default gateway

For removing the default gateway:

```bash
juju run-action <unit> remove-default-gw --wait
```

## Relations

- **lte-vepc**: LTE VEPC Interface. Shares enodeB's MME address.
