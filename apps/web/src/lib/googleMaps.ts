/** Parse coordinates from Google Maps share links or raw "lat, lng" text. */

export type LatLng = {latitude: number; longitude: number};

const COORD = String.raw`(-?\d+(?:\.\d+)?)`;
const PAIR = new RegExp(`${COORD}\\s*,\\s*${COORD}`);

function valid(latitude: number, longitude: number): LatLng | null {
  if(!Number.isFinite(latitude)||!Number.isFinite(longitude))return null;
  if(latitude<-90||latitude>90||longitude<-180||longitude>180)return null;
  return {
    latitude: Number(latitude.toFixed(6)),
    longitude: Number(longitude.toFixed(6)),
  };
}

function fromPair(text: string): LatLng | null {
  const match = text.match(PAIR);
  if(!match)return null;
  return valid(Number(match[1]), Number(match[2]));
}

export function isGoogleMapsShortUrl(value: string): boolean {
  try{
    const host = new URL(value.trim()).hostname.toLowerCase();
    return host==="maps.app.goo.gl"||host==="goo.gl"||host.endsWith(".app.goo.gl");
  }catch{
    return false;
  }
}

export function parseGoogleMapsLocation(input: string): LatLng | null {
  const text = input.trim();
  if(!text)return null;

  const raw = text.match(new RegExp(`^${COORD}\\s*,\\s*${COORD}$`));
  if(raw)return valid(Number(raw[1]), Number(raw[2]));

  // Place pin markers are more precise than the map camera center.
  const pin = text.match(new RegExp(`!3d${COORD}!4d${COORD}`));
  if(pin)return valid(Number(pin[1]), Number(pin[2]));

  const at = text.match(new RegExp(`@${COORD},${COORD}`));
  if(at)return valid(Number(at[1]), Number(at[2]));

  try{
    const url = new URL(text.includes("://")?text:`https://${text}`);
    for(const key of ["q","query","ll","center","destination","daddr"]){
      const value = url.searchParams.get(key);
      if(!value)continue;
      const coords = fromPair(decodeURIComponent(value));
      if(coords)return coords;
    }
  }catch{
    // Not a URL — fall through.
  }

  return fromPair(text);
}

export function googleMapsOpenUrl(latitude: number, longitude: number): string {
  return `https://www.google.com/maps?q=${latitude},${longitude}`;
}

export function googleMapsEmbedUrl(latitude: number, longitude: number): string {
  return `https://maps.google.com/maps?q=${latitude},${longitude}&z=16&output=embed`;
}
