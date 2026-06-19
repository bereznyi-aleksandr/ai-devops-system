# BEM-947 Claude role failure diagnostic

Trace: `bem947_object_dispatch_after_yaml_validation_20260619T1935Z`
Selected run: `27845000228`
Report commit: `9b53344878f6a6bed8ea8e21844452faa8cc962c` 

## Sanitized excerpts

- `full: claude	Set up job	﻿2026-06-19T19:36:30.5611371Z Current runner version: '2.335.1'`
- `full: claude	Set up job	2026-06-19T19:36:30.5637441Z ##[group]Runner Image Provisioner`
- `full: claude	Set up job	2026-06-19T19:36:30.5638351Z Hosted Compute Agent`
- `full: claude	Set up job	2026-06-19T19:36:30.5639104Z Version: 20260611.554`
- `full: claude	Set up job	2026-06-19T19:36:30.5639769Z Commit: 5e0782fdc9014723d3be820dd114dd31555c2bd1`
- `full: claude	Set up job	2026-06-19T19:36:30.5640557Z Build Date: 2026-06-11T21:40:46Z`
- `full: claude	Set up job	2026-06-19T19:36:30.5641294Z Worker ID: {9e8975f8-bff9-48fe-b681-1cc5ab4d304f}`
- `full: claude	Set up job	2026-06-19T19:36:30.5642453Z Azure Region: eastus`
- `full: claude	Set up job	2026-06-19T19:36:30.5643185Z ##[endgroup]`
- `full: claude	Set up job	2026-06-19T19:36:30.5645091Z ##[group]Operating System`
- `full: claude	Set up job	2026-06-19T19:36:30.5645848Z Ubuntu`
- `full: claude	Set up job	2026-06-19T19:36:30.5646425Z 24.04.4`
- `full: claude	Set up job	2026-06-19T19:36:30.5646978Z LTS`
- `full: claude	Set up job	2026-06-19T19:36:30.5647619Z ##[endgroup]`
- `full: claude	Set up job	2026-06-19T19:36:30.5648194Z ##[group]Runner Image`
- `full: claude	Set up job	2026-06-19T19:36:30.5648893Z Image: ubuntu-24.04`
- `full: claude	Set up job	2026-06-19T19:36:30.5649486Z Version: 20260615.205.1`
- `full: claude	Set up job	2026-06-19T19:36:30.5650742Z Included Software: https://github.com/actions/runner-images/blob/ubuntu24/20260615.205/images/ubuntu/Ubuntu2404-Readme.md`
- `full: claude	Set up job	2026-06-19T19:36:30.5652731Z Image Release: https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20260615.205`
- `full: claude	Set up job	2026-06-19T19:36:30.5653853Z ##[endgroup]`
- `full: claude	Set up job	2026-06-19T19:36:30.5655277Z ##[group]GITHUB_TOKEN Permissions`
- `full: claude	Set up job	2026-06-19T19:36:30.5657739Z Actions: write`
- `full: claude	Set up job	2026-06-19T19:36:30.5658405Z Contents: write`
- `full: claude	Set up job	2026-06-19T19:36:30.5659048Z Issues: write`
- `full: claude	Set up job	2026-06-19T19:36:30.5659705Z Metadata: read`
- `full: claude	Set up job	2026-06-19T19:36:30.5660354Z PullRequests: write`
- `full: claude	Set up job	2026-06-19T19:36:30.5660998Z ##[endgroup]`
- `full: claude	Set up job	2026-06-19T19:36:30.5663329Z Secret source: Actions`
- `full: claude	Set up job	2026-06-19T19:36:30.5664611Z Prepare workflow directory`
- `full: claude	Set up job	2026-06-19T19:36:30.5999814Z Prepare all required actions`
- `full: claude	Set up job	2026-06-19T19:36:30.6038694Z Getting action download info`
- `full: claude	Set up job	2026-06-19T19:36:30.8285402Z Download action repository 'actions/checkout@v4' (SHA:34e114876b0b11c390a56381ad16ebd13914f8d5)`
- `full: claude	Set up job	2026-06-19T19:36:30.9060364Z Download action repository 'anthropics/claude-code-action@v1' (SHA:51705da45eecce209d4700538bf8377d5b5fc695)`
- `full: claude	Set up job	2026-06-19T19:36:31.1722650Z Getting action download info`
- `full: claude	Set up job	2026-06-19T19:36:31.2407329Z Download action repository 'oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6' (SHA:0c5077e51419868618aeaa5fe8019c62421857d6)`
- `full: claude	Set up job	2026-06-19T19:36:31.4706253Z Getting action download info`
- `full: claude	Set up job	2026-06-19T19:36:31.6231278Z Getting action download info`
- `full: claude	Set up job	2026-06-19T19:36:31.8602601Z Complete job name: claude`
- `full: claude	Checkout repository	﻿2026-06-19T19:36:31.9590739Z Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true environment variable. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/`
- `full: claude	Checkout repository	2026-06-19T19:36:31.9602205Z ##[group]Run actions/checkout@v4`

## Result

BLOCKED: claude_role outcome=failure; executed/completed proof remains absent.
