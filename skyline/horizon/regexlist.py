import re
import settings

class RegexList:
  """ Maintain a list of regex for matching"""

  def __init__(self, regex_list):
    self.regex_list = map(lambda r: re.compile(r), regex_list)

  def __contains__(self, value):
    for regex in self.regex_list:
      if regex.search(value):
        return True
    return False

  def __nonzero__(self):
    return bool(self.regex_list)

WhiteList = RegexList(settings.WHITELIST)
BlackList = RegexList(settings.BLACKLIST)
