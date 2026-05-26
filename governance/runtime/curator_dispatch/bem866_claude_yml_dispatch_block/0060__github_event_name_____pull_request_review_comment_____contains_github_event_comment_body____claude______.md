# claude.yml dispatch block line
Line: 60
Text:       (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
