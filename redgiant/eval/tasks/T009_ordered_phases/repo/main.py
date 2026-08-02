from util import slug


def title_line(text):
    # deve produrre "titolo | titolo-come-slug"
    return text + " | " + text.lower()
