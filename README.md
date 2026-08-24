# ha-holdsport

Holdsport integration for Home Assistant (HACS custom integration).

## Features

- Config flow with Holdsport credentials (username/password or managed profile ID)
- Polls and exposes:
  - user profile
  - teams
  - activities
  - members
  - notes
  - activity tasks
- Sensors:
  - user profile sensor
  - per-team next activity sensor (with detailed attributes)
  - per-team activity/member/note count sensors
- Services:
  - `holdsport.execute_activity_action`
  - `holdsport.add_activity_comment`
  - `holdsport.add_activity_ride`
  - `holdsport.remove_activity_ride`
  - `holdsport.assign_activity_task`

## Installation

[![Open your Home Assistant instance and open the repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MrMEEE&repository=ha-holdsport)

### HACS

1. In HACS, add this repository as a **Custom repository** with type **Integration**.
2. Install **Holdsport** from HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add integration**, then add **Holdsport**.

### Manual

1. Download the latest release zip from GitHub.
2. Extract the contents to a folder named `holdsport` in your Home Assistant `custom_components` directory.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add integration**, then add **Holdsport**.

## Notes

- Data is fetched from `https://api.holdsport.dk/v1`.
- Update interval is configurable in the integration options.
