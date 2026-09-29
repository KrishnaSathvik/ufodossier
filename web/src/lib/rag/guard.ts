export const OFF_TOPIC_TEXT =
  "That isn't covered by the records in this archive. You can ask about a sighting, a place, a year, an agency, or a released file.";

const ARCHIVE = /\b(ufo|uap|ua?ps|sightings?|archive|dossier|pursue|aaro|war\.gov|fbi|cia|nsa|nasa|dia|nro|usaf|navy|air force|army|radar|releases?|audios?|videos?|photos?|images?|maps?|documents?|files?|incidents?|cases?|roswell|tremonton|gemini|apollo|blue book|objects?|craft|pilots?|astronauts?|declassified)\b/i;

const OFF_TOPIC = /\b(weather|forecast|recipe|recipes|cook|bake|bitcoin|crypto|ethereum|stock price|python|javascript|typescript|homework|poem|joke|jokes|movie|song|lyrics|nba|nfl|mlb|world cup|translate this|capital of|president of|write (me )?(code|a poem|a story|an email)|how do i (hack|code)|what is the weather|who won)\b/i;

export function isOffTopic(question: string): boolean {
  const text = question.trim();
  if (!text) return true;
  if (ARCHIVE.test(text)) return false;
  if (OFF_TOPIC.test(text)) return true;
  if (/^(hi|hello|hey|thanks|thank you|who are you|what can you do)\b/i.test(text)) return true;
  return false;
}
