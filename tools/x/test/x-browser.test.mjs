import test from "node:test";
import assert from "node:assert/strict";
import { extractCreatedPostId } from "../src/x-browser.mjs";

test("extracts the created post id from the X GraphQL response shape", () => {
  const payload = {
    data: {
      create_tweet: {
        tweet_results: {
          result: { rest_id: "1234567890123456789" },
        },
      },
    },
  };
  assert.equal(extractCreatedPostId(payload), "1234567890123456789");
});

test("extracts the created post id from the X API v2 response shape", () => {
  assert.equal(extractCreatedPostId({ data: { id: "1234567890123456789", text: "hello" } }), "1234567890123456789");
});

test("does not mistake an unrelated user id for a publication receipt", () => {
  assert.equal(extractCreatedPostId({ data: { user: { rest_id: "1234567890123456789" } } }), null);
});
