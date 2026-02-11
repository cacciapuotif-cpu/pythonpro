module.exports = {
  extends: ['react-app', 'react-app/jest'],
  rules: {
    'no-restricted-imports': [
      'error',
      {
        paths: [
          {
            name: 'axios',
            message:
              'Direct axios imports are not allowed. Please use the shared http client from "lib/http.js" instead. This ensures consistent baseURL, auth tokens, and error handling.',
          },
        ],
        patterns: [
          {
            group: ['axios'],
            message:
              'Direct axios imports are not allowed. Please use the shared http client from "lib/http.js" instead.',
          },
        ],
      },
    ],
  },
  overrides: [
    {
      // Allow axios import only in http.js and test files
      files: ['**/lib/http.js', '**/*.test.js', '**/*.spec.js', '**/setupTests.js'],
      rules: {
        'no-restricted-imports': 'off',
      },
    },
  ],
};
