# Octave

Octave is an Electron desktop application for gesture and voice-based desktop control on Windows.

## Recommended IDE Setup

- [VSCode](https://code.visualstudio.com/) + [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint) + [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

## Project Setup

### Install

```bash
$ npm install
```

### Development

```bash
$ npm run dev
```

### Build

```bash
# For windows
$ npm run build:win

# For macOS
$ npm run build:mac

# For Linux
$ npm run build:linux
```

## Windows Release

The Windows installer is generated at:

```bash
dist/Octave-1.1.0-setup.exe
```

The unpacked app for smoke testing is generated at:

```bash
dist/win-unpacked/
```

## Release Notes

See [CHANGELOG.md](./CHANGELOG.md) for the `1.1.0` release summary.
