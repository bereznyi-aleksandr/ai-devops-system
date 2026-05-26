# claude.yml dispatch block line
Line: 58
Text:       (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude') && !contains(github.event.comment.body, '@analyst') && !contains(github.event.comment.body, '@auditor') && !contains(github.event.comment.body, '@executor')) ||
