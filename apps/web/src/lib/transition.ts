const MINIMUM_AUTH_TRANSITION_MS = 1_000;

export async function waitForAuthTransition(startedAt:number):Promise<void>{
  const remaining=MINIMUM_AUTH_TRANSITION_MS-(Date.now()-startedAt);
  if(remaining>0)await new Promise(resolve=>window.setTimeout(resolve,remaining));
}
