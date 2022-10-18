# SRS-ENB-UE-Operator

Open-source 4G EnodeB and User emulators developed by [Software Radio Systems (SRS)](https://www.srslte.com/).

## Usage

Create a YAML configuration file with the necessary charm config:

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
juju deploy charmed-osm-srs-enb-ue --config <yaml config file> --channel=edge
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
- **lte-core**: LTE Core Interface. Shares enodeB'.
