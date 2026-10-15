# Changelog

All notable changes to this project will be documented in this file.
## [0.2.4] - 2026-10-15

### Bug Fixes

- Zero threshold crash, options flow on old HA, pruning and sleep-safe time

### Documentation

- Update test count in CLAUDE.md

## [0.2.3] - 2026-10-15

### Bug Fixes

- Sort manifest keys, fix services.yaml targets, add CONFIG_SCHEMA, clean hacs.json
- Use entity target filter in services.yaml (hassfest rejects device filter)
- Add brand/icon.png for HACS brands validation
- Support HA 2026.10 probatio schemas
- Support both async_extract_config_entry_ids signatures

### Dependencies

- **deps**: Pin dependencies
- **deps**: Lock file maintenance (#15)
- **deps**: Lock file maintenance (#16)
- **deps**: Lock file maintenance (#17)
- **deps**: Lock file maintenance (#18)
- **deps**: Update codecov/codecov-action digest to e79a696 (#19)
- **deps**: Lock file maintenance (#20)
- **deps**: Update home-assistant/actions digest to 868e6cb (#21)
- **deps**: Lock file maintenance (#22)
- **deps**: Update actions/checkout digest to df4cb1c (#23)
- **deps**: Update codecov/codecov-action digest to fb8b358 (#26)
- **deps**: Lock file maintenance (#27)
- **deps**: Update hacs/action digest to 1ebf01c (#28)
- **deps**: Update home-assistant/actions digest to d05c253 (#29)
- **deps**: Update home-assistant/actions digest to e91ad19 (#30)
- **deps**: Lock file maintenance (#31)
- **deps**: Lock file maintenance (#33)
- **deps**: Update home-assistant/actions digest to f4ca6f6 (#34)
- **deps**: Lock file maintenance (#35)
- **deps**: Lock file maintenance (#36)
- **deps**: Lock file maintenance (#37)
- **deps**: Update actions/checkout digest to d23441a (#38)
- **deps**: Update home-assistant/actions digest to e3fb68e (#39)
- **deps**: Lock file maintenance (#41)
- **deps**: Update home-assistant/actions digest to ab22029 (#42)
- **deps**: Lock file maintenance (#43)
- **deps**: Update home-assistant/actions digest to a7c616c (#44)
- **deps**: Lock file maintenance (#45)
- **deps**: Lock file maintenance (#47)
- **deps**: Lock file maintenance (#48)
- **deps**: Lock file maintenance (#49)
- **deps**: Update orhun/git-cliff-action digest to 3d96a18 (#50)
- **deps**: Lock file maintenance (#51)
- **deps**: Update home-assistant/actions digest to 58bff37 (#52)
- **deps**: Lock file maintenance (#53)
- **deps**: Update orhun/git-cliff-action digest to a9a9552 (#54)
- **deps**: Lock file maintenance (#55)
- **deps**: Update home-assistant/actions digest to 06749dd (#56)
- **deps**: Lock file maintenance (#57)
- **deps**: Lock file maintenance (#58)
- **deps**: Lock file maintenance (#61)
- **deps**: Update home-assistant/actions digest to 50baf3a (#62)
- **deps**: Update astral-sh/setup-uv action to v10
- **deps**: Update actions/checkout action to v7
- **deps**: Update codecov/codecov-action action to v7

## [0.2.1] - 2026-04-26

### Dependencies

- **deps**: Update codecov/codecov-action action to v6
- **deps**: Update astral-sh/setup-uv action to v8
- **deps**: Update actions/checkout action to v6
- **deps**: Pin orhun/git-cliff-action action to f50e115

### Documentation

- Add conventional commit conventions to README, CLAUDE.md, and GEMINI.md

## [0.2.0] - 2026-04-21

### Bug Fixes

- Update renovate configuration to use best-practices preset
- Quote git commit command and auto-push tags in release task

### Dependencies

- **deps**: Update astral-sh/setup-uv action to v7
- **deps**: Pin dependencies

### Features

- Update dashboard preview in README
- Replace release-please with git-cliff

## [0.1.3] - 2026-04-21

### Features

- Add resized icons for HACS and Home Assistant integration

## [0.1.1] - 2026-04-21

### Bug Fixes

- Migrate entity services to domain services and add documentation
- Resolve CI dependency resolution issues
- Resolve CI type errors while maintaining compatibility
- CI dependency conflicts and HA pinning
- Taskfile syntax error in release task
- Taskfile yaml syntax error in release description

### Documentation

- Update github account and service targeting examples
- Include all sensors in dashboard examples

### Features

- Add sensor for number of consumptions today

### Style

- Fix import sorting and formatting

