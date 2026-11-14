# Zabbix templates for Huawei OptiX RTN microwave radios

SNMP templates for Huawei OptiX RTN radios (RTN 905, 910A, 950A, 980 and 380H), for Zabbix 6.0 and 7.0.

The templates and their documentation are in the layout of the
[Zabbix community templates](https://github.com/zabbix/community-templates) repository:

```
Network_Devices/Huawei/template_huawei_optix_rtn_snmp/
├── 6.0/
│   ├── README.md                            what the template monitors, setup, macros, items, triggers
│   └── template_huawei_optix_rtn_snmp.yaml  import this into Zabbix 6.0
└── 7.0/
    ├── README.md
    └── template_huawei_optix_rtn_snmp.yaml  import this into Zabbix 7.0
```

To use the templates, import the YAML for your Zabbix version and read the README next to it.

## Building

The YAML files are generated; do not edit them by hand. Change `generator/build_templates.py` and run:

```
pip install pyyaml
python3 generator/build_templates.py   # writes both YAML files
python3 generator/make_readme.py       # writes both READMEs from the YAML
```

Every item is defined once in the generator and rendered for both Zabbix versions, with stable UUIDs, so re-importing
a new build updates existing hosts in place.

`generator/data/optix_enums.json` holds the value names used for value maps (modulation modes, channel bandwidths,
alarm IDs), taken from the Huawei OPTIX MIBs.

## License

MIT, see [LICENSE](LICENSE).
