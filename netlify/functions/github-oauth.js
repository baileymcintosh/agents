/**
 * Exchanges a GitHub OAuth code for an access token.
 * Called by the frontend after GitHub redirects back with ?code=xxx.
 * GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET are set as Netlify env vars.
 */
export const handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' }
  }

  let code
  try {
    const body = JSON.parse(event.body || '{}')
    code = body.code
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid request body' }) }
  }

  if (!code) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing code' }) }
  }

  const clientId = process.env.GITHUB_CLIENT_ID
  const clientSecret = process.env.GITHUB_CLIENT_SECRET

  if (!clientId || !clientSecret) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'OAuth app not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in Netlify env vars.' }),
    }
  }

  try {
    const res = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        code,
      }),
    })

    const data = await res.json()

    if (data.error) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: data.error_description || data.error }),
      }
    }

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_token: data.access_token }),
    }
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Failed to exchange code: ' + err.message }),
    }
  }
}
