FLASK_APP=app
FLASK_ENV=development
# Prevent IDE saves to tests/ / migrations/ / static/ from reloading the server
FLASK_RUN_EXCLUDE_PATTERNS=*/tests/*,*/migrations/*,*/static/*,*/utils/*,*/.git/*
