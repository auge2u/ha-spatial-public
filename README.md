# HA Spatial

Spatial, human-centric room mapping for Home Assistant: capture a room from a few
photos (or import an iOS RoomPlan scan), get a real-world-scale floorplan, and place
your entities in it. Registers an admin sidebar panel at `/ha-spatial`.

> This is the public distribution repository for the HA Spatial integration.
> Development happens in a private repository; releases here are the packaged,
> installable integration.

## Requirements

- Home Assistant 2025.5.0 or newer

## Install via HACS

1. HACS → **Integrations** → three-dot menu (⋮) → **Custom repositories**
2. Add repository `https://github.com/auge2u/ha-spatial-public` with category **Integration**
3. Find **HA Spatial** in the HACS list and click **Download**
4. Restart Home Assistant
5. Settings → **Devices & services** → **Add integration** → search for **HA Spatial**

HACS installs from the `ha-spatial.zip` asset attached to the latest GitHub release.

## Manual install

Download `ha-spatial-v<version>.zip` from the latest release and extract it into your
Home Assistant configuration directory (it contains `custom_components/ha_spatial/`),
then restart Home Assistant.

## Privacy

Room photos you capture are processed to build a spatial model and are not sent
anywhere except the vision provider you explicitly configure. See the in-app privacy
notes on every screen that touches photos.
