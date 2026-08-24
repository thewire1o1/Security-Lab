# APOTHEON ONE Mobile Provisioning

> **Unified. Elevated.**  
> Development & Security Platform by Digital Paragon

APOTHEON ONE treats mobile development as a first-class platform domain while keeping platform-specific build requirements explicit.

## Flutter

The `flutter` profile is locally executable in the Linux control plane. APOTHEON ONE reuses a system Flutter installation when available; otherwise it installs the official stable Flutter SDK under the persistent toolchain directory. Generated projects include Android, iOS, and web sources. Local bounded validation uses `flutter analyze`, `flutter test`, and `flutter build web`. Android packaging remains available as a separate project command, and a generated GitHub Actions workflow provides repeatable CI validation.

## React Native

The `react-native` profile uses the current React Native Community CLI noninteractively and requires Node.js 22.13 or newer. It generates native Android and iOS projects, installs npm dependencies, disables nested Git initialization, and skips CocoaPods installation on the Linux control plane. Local bounded validation covers lint and JavaScript/TypeScript tests; Android builds are represented separately and in the generated CI workflow.

## Native Android

The `android` profile generates a minimal native Kotlin application targeting Android API 37 with Android Gradle Plugin 9.3 and Gradle 9.5. APOTHEON ONE does not silently accept Android SDK licenses or install a full Android build environment into the control-plane Codespace. Native Android compilation is assigned to the generated GitHub Actions workflow on an Ubuntu runner, where the required SDK packages are installed explicitly.

## Native iOS

The `ios` profile generates SwiftUI source and XcodeGen project metadata. The Linux control plane does not pretend to provide Xcode. The generated workflow uses a GitHub-hosted macOS runner, installs XcodeGen, creates the Xcode project, and performs a simulator build with code signing disabled. Signing and App Store release credentials remain outside project scaffolding.

## Project boundaries

Managed mobile projects are created under the persistent project root and registered in the same project registry as web, API, full-stack, and security projects. Failed new-project provisioning is cleaned only when the target is inside the managed project root. Existing or externally registered paths are never recursively removed by the provisioner.

Long-running development servers and platform builds that require external runners are not executed synchronously through MCP. Generated CI workflows provide the boundary for those operations.
