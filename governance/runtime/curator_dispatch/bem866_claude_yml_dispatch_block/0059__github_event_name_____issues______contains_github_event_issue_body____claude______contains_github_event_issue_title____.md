# claude.yml dispatch block line
Line: 59
Text:       (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude'))) ||
