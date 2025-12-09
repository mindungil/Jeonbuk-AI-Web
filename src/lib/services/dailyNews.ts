const NEWS_PROXY_ENDPOINT = '/api/v1/utils/news';

type NewsArticle = {
	title?: string;
	date?: string;
	description?: string;
};

type NewsResponse = Record<string, NewsArticle[]>;

const stripHtmlTags = (value: string) => value.replace(/<[^>]+>/g, '');

export type NewsItem = {
	category: string;
	title: string;
	date: string;
	summary: string;
	url?: string;
};

export const shouldShowDailyNews = (lastActiveAt?: number | null) => {
	if (!lastActiveAt) {
		return true;
	}

	const startOfToday = new Date();
	startOfToday.setHours(0, 0, 0, 0);

	return lastActiveAt < Math.floor(startOfToday.getTime() / 1000);
};

export const fetchDailyNews = async (
	employeeName: string,
	apiUrl: string = NEWS_PROXY_ENDPOINT
): Promise<NewsResponse> => {
	const token = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null;

	const response = await fetch(apiUrl, {
		method: 'POST',
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			...(token ? { Authorization: `Bearer ${token}` } : {})
		},
		body: JSON.stringify({ employee_name: employeeName })
	});

	if (!response.ok) {
		throw new Error('Failed to fetch news');
	}

	return (await response.json()) as NewsResponse;
};

export const parseDailyNews = (payload: NewsResponse): NewsItem[] => {
	if (!payload || typeof payload !== 'object') throw new Error('Invalid news payload');

	const items = Object.entries(payload).flatMap(([category, articles]) => {
		if (!Array.isArray(articles) || articles.length === 0) return [];

		return articles
			.map((article) => {
				const rawTitle = article?.title ?? '';
				const rawDescription = article?.description ?? '';

				return {
					category,
					title: stripHtmlTags(rawTitle).trim(),
					date: article?.date ?? '',
					summary: stripHtmlTags(rawDescription).replace(/\s+/g, ' ').trim(),
					url: article?.url || article?.link || article?.originallink || ''
				};
			})
			.filter((item) => item.title || item.summary);
	});

	if (!items.length) throw new Error('No news items');

	return items;
};

export const getDailyNewsItems = async (
	employeeName: string,
	apiUrl?: string
): Promise<NewsItem[]> => {
	const targetUrl = apiUrl ?? NEWS_PROXY_ENDPOINT;
	const news = await fetchDailyNews(employeeName, targetUrl);
	return parseDailyNews(news);
};
