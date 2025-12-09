<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import type { NewsItem } from '$lib/services/dailyNews';

	export let show = false;
	export let items: NewsItem[] = [];
	export let error: string | null = null;

	const groupByCategory = (data: NewsItem[]) => {
		const grouped: Record<string, NewsItem[]> = {};
		for (const item of data) {
			if (!grouped[item.category]) grouped[item.category] = [];
			grouped[item.category].push(item);
		}
		return Object.entries(grouped);
	};
</script>

<Modal bind:show={show} size="md">
	<div class="p-6 space-y-4">
		<div class="text-lg font-semibold text-gray-900 dark:text-gray-50">오늘의 뉴스</div>

		{#if error}
			<div class="text-sm text-gray-700 dark:text-gray-200 whitespace-pre-wrap">{error}</div>
		{:else}
			<div class="space-y-6">
				{#each groupByCategory(items) as [category, categoryItems]}
					<section class="space-y-3">
						<div class="text-base font-semibold text-gray-800 dark:text-gray-100">{category}</div>
						<div class="space-y-3">
							{#each categoryItems as item}
								<div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/60 p-4 space-y-2">
									<div class="text-sm font-medium text-gray-900 dark:text-gray-50">{item.title}</div>
									{#if item.date}
										<div class="text-xs text-gray-600 dark:text-gray-400">{item.date}</div>
									{/if}
									{#if item.url}
										<a
											class="text-xs text-blue-700 dark:text-blue-300 underline"
											href={item.url}
											target="_blank"
											rel="noreferrer"
										>
											원문 링크
										</a>
									{/if}
									{#if item.summary}
										<div class="text-sm leading-6 text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
											{item.summary}
										</div>
									{/if}
								</div>
							{/each}
						</div>
					</section>
				{/each}
			</div>
		{/if}
	</div>
</Modal>
