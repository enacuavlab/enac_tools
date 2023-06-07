
# ENAC HLAs

Various HLAs used in the ENAC lab.

* Pprzlink
* CUI Devices - AMT22

# Requirements

The Pprzlink analyser need lxml, installed with the same python version Logic2 uses: python3.8.

Install python3.8 and pip:

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.8-distutils
wget https://bootstrap.pypa.io/get-pip.py
python3.8 get-pip.py
```

Install the required modules in the `lib` directory:

`python3.8 -m pip instakk -r requirements.txt --target lib`

Set the `PAPARAZZI_HOME` environnement variable, or change the `DEFAULT_PPRZ_HOME` in Pprzlink.py:5.

## AMT22

Decode SPI AMT22 encoders from CUI Devices


## Pprzlink

Decode Pprzlink transparent telemetry.
Only transparent pprzlink v2.0 is supported at the moment.
