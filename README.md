# ERC-UCU-Drone-2026



### NetworkManager configuration

*ssid:* erso_drone
*password:* 12345678

Creating hot spot

```
sudo nmcli device wifi hotspot con-name erso_drone ssid erso_drone password 12345678
```

New IP-address will be `10.42.0.1`

Disable hotspot

```
sudo nmcli connection down erso_drone
```