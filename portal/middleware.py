from __future__ import annotations

from django.http import QueryDict


class FilterStateMiddleware:
    """Restore compact, session-backed list filter state for long filter URLs.

    ScoutBox list screens can contain hundreds of repeated filter values. Browsers and
    the development server can reject those GET request lines before Django sees them.
    The browser stores the expanded query via a small POST and then navigates with only
    ``?fs=<token>``. This middleware expands that token back into ``request.GET`` for
    the existing read-only list views, so pagination/sorting/filter code stays simple.
    """

    SESSION_KEY = 'scoutbox_filter_states_v1'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.scoutbox_filter_state_token = ''
        if request.method == 'GET':
            token = str(request.GET.get('fs') or '').strip()
            if token and hasattr(request, 'session'):
                states = request.session.get(self.SESSION_KEY) or {}
                state = states.get(token) if isinstance(states, dict) else None
                if isinstance(state, dict) and state.get('path') == request.path:
                    pairs = state.get('pairs') or []
                    restored = QueryDict('', mutable=True)
                    for pair in pairs:
                        if isinstance(pair, (list, tuple)) and len(pair) == 2:
                            name, value = str(pair[0]), str(pair[1])
                            if name and name != 'fs':
                                restored.appendlist(name, value)
                    # Explicit compact-URL parameters (page/sort/export/date overrides)
                    # take precedence over the saved state.
                    for name in request.GET.keys():
                        if name == 'fs':
                            continue
                        restored.setlist(name, request.GET.getlist(name))
                    request.GET = restored
                    request.scoutbox_filter_state_token = token
        return self.get_response(request)
