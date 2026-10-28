const axios = require("axios");
const qs = require("querystring");
require("dotenv").config();

const clientId = process.env.SPOTIFY_CLIENT_ID;
const clientSecret = process.env.SPOTIFY_CLIENT_SECRET;

const getToken = async () => {
  const tokenUrl = "https://accounts.spotify.com/api/token";
  const data = qs.stringify({ grant_type: "client_credentials" });
  const config = {
    headers: {
      Authorization: `Basic ${Buffer.from(
        `${clientId}:${clientSecret}`
      ).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
  };

  try {
    const response = await axios.post(tokenUrl, data, config);
    return response.data.access_token;
  } catch (error) {
    console.error("Error fetching access token:", error);
  }
};

const getFirstResultSpotify = async (query) => {
  const token = await getToken();
  const searchUrl = `https://api.spotify.com/v1/search?q=${encodeURIComponent(
    query
  )}&type=track&limit=1`;

  const config = {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };

  try {
    const response = await axios.get(searchUrl, config);
    if (response.data.tracks.items.length > 0) {
      const firstResult = response.data.tracks.items[0];
      return firstResult.external_urls.spotify;
    } 
    else {
      return "No results found.";
    }
  } catch (error) {
    if (error.response && error.response.status === 429) {
      const retryAfter = error.response.headers["retry-after"];
      console.log(`Rate limited. Retrying after ${retryAfter} seconds.`);
      await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
      return getFirstResultSpotify(query);
    } 
    else {
      console.error("Error making request:", error.message);
    }
  }
};

module.exports = { getFirstResultSpotify };
