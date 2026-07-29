export const emojiMap = {
  ':smile:': '\u{1F60A}', ':laughing:': '\u{1F602}', ':wink:': '\u{1F609}', ':heart:': '\u2764\uFE0F',
  ':thumbsup:': '\u{1F44D}', ':thumbsdown:': '\u{1F44E}', ':clap:': '\u{1F44F}', ':fire:': '\u{1F525}',
  ':rocket:': '\u{1F680}', ':star:': '\u2B50', ':check:': '\u2705', ':x:': '\u274C',
  ':warning:': '\u26A0\uFE0F', ':bulb:': '\u{1F4A1}', ':question:': '\u2753', ':info:': '\u2139\uFE0F',
  ':gear:': '\u2699\uFE0F', ':lock:': '\u{1F512}', ':key:': '\u{1F511}', ':bug:': '\u{1F41B}',
  ':chart:': '\u{1F4CA}', ':code:': '\u{1F4BB}', ':file:': '\u{1F4C4}', ':folder:': '\u{1F4C1}',
  ':search:': '\u{1F50D}', ':link:': '\u{1F517}', ':mail:': '\u{1F4E7}', ':pen:': '\u270D\uFE0F',
  ':sparkles:': '\u2728', ':tada:': '\u{1F389}', ':package:': '\u{1F4E6}', ':book:': '\u{1F4D6}',
}

export function replaceEmojiShortcodes(text) {
  return text.replace(/:[\w+-]+:/g, (match) => emojiMap[match] || match)
}
