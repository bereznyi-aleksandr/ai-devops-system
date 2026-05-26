# BEM-866 exact workflow presence
File: .github/workflows/claude.yml
- exists: True
- has_workflow_dispatch: True
- has_inputs: True
- has_trace_id: True
- has_from_claude: True
- has_git_push: True

Prefix:
name: Claude Code

# BEM-477: added transport result write + file report
# BEM-488: YAML-safe rewrite — no f-string multiline, Python-based summary
# NO createComment to issue #31 (locked at 2500 comments)

on:
  workflow_dispatch:
    inputs:
      role:
        description: 'analyst | auditor | executor | curator'
        required: true
        type: string
      provider:
        description: 'claude'
        required: false
        default: 'claude'
        type: string
      trace_id:
        description: 'Trace id'
        required: true
        type: string
      cycle_id:
        description: 'Role cycle id'
        required: false
        default: ''
        type: string
      task_type:
        description: 'Task type'
        required: false
        default: 'default_development'
        type: string
      task:
        description: 'Task body'
        required: false
        default: ''
        type: string
  issue_comment:
    types: [created]
  issues:
    types: [opened, assigned]
  pull_request_review_comment:
    types: [created]
  pull_request_review:
    types: [submitted]

permissions:
  contents: write
  pull-requests: write
  issues: write
  id-token: write
  actions: write

jobs:
  claude:
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude') && !contains(github.event.comment.body, '@analyst') && !contains(github.event.comment.body, '@auditor') && !contains(github.event.comment.body, '@executor')) ||
      (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude'))) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude'))

    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          token: ${{ secrets.AI_SYSTEM_GITHUB_PAT }}

      - name: Build Claude role prompt
        if: github.event_name == 'workflow_dispatch'
        shell: bash
        env:
          INPUT_ROLE:      ${{ inputs.role }}
          INPUT_PROVIDER:  ${{ inputs.provider }}
          INPUT_TRACE_ID:  ${{ inputs.trace_id }}
          INPUT_CYCLE_ID:  ${{ inputs.cycle_id }}
          INPUT_TASK_TYPE: ${{ inputs.task_type }}
    
