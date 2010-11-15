import re

class Snippet(object):
    def __init__(self, snippet, variant):
        self.snippet = snippet
        self.variant = variant
        self.comment = ''
        self.body = []

    def get_body_and_offsets(self):
        tab_offsets = {}
        insert_offsets = {}
        replaces = {}
        matcher = re.compile(ur'\$\{(\d+)(:(.*?))?\}')
        for m in matcher.finditer(self.body):
            if m.group(3):
                replaces[int(m.group(1))] = m.group(3)

        delta = [0]
        def replace_stops(match):
            idx = int(match.group(1))
            replace = replaces.get(idx, u'')

            start = delta[0] + match.start()
            delta[0] += len(replace) - match.end() + match.start()
            end = delta[0] + match.end()

            tab_offsets[idx] = start, end

            return replace

        def replace_inserts(match):
            idx = int(match.group(1))
            replace = replaces.get(idx, u'')

            start = delta[0] + match.start()
            dt = len(replace) - match.end() + match.start()
            delta[0] += dt
            end = delta[0] + match.end()

            for k, (s, e) in tab_offsets.iteritems():
                if s >= start: s += dt
                if e >= start: e += dt
                tab_offsets[k] = s, e

            insert_offsets[idx] = start, end

            return replace

        body = matcher.sub(replace_stops, self.body)

        delta[0] = 0
        body = re.sub(ur'\$(\d+)', replace_inserts, body)

        return body, tab_offsets, insert_offsets


def parse_snippets_from(filename):
    pl = ''
    csnippet = None
    snippets = {}
    for l in open(filename).read().decode('utf-8').splitlines():
        if l.startswith('snippet'):
            tag_and_variant = l.split(None, 3)[1:]
            if len(tag_and_variant) == 2:
                tag, variant = tag_and_variant
                key = ' '.join(tag_and_variant)
            else:
                tag, variant = tag_and_variant[0], None
                key = tag
            csnippet = Snippet(tag, variant)
            snippets[key] = csnippet
            if pl.startswith('#'):
                csnippet.comment = pl[1:].strip()
        elif l.startswith('\t') and csnippet:
            csnippet.body.append(l[1:])

        pl = l

    for s in snippets.values():
        s.body = u'\n'.join(s.body)

    return snippets