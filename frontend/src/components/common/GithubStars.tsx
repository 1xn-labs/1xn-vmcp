import React from 'react';

export function GithubStars({ repo }: { repo: string }) {
  const [stars, setStars] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetch(`https://api.github.com/repos/${repo}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.stargazers_count !== undefined) {
          setStars(data.stargazers_count);
        } else {
          setError('N/A');
        }
      })
      .catch(() => setError('N/A'));
  }, [repo]);

  if (error) return <span className="ml-1 bg-gray-800 text-gray-300 rounded px-2 py-0.5 text-xs font-mono border border-gray-700">★ {error}</span>;
  if (stars === null) return <span className="ml-1 bg-gray-800 text-gray-300 rounded px-2 py-0.5 text-xs font-mono border border-gray-700 animate-pulse">★ ...</span>;
  return <span className="ml-1 bg-gray-800 text-white rounded px-2 py-0.5 text-xs font-mono border border-gray-700">★ {stars}</span>;
}
