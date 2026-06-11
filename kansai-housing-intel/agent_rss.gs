// agent_rss.gs - GoogleニュースRSS収集・パース

const RSS_FEEDS = [
  {
    category: 'housing_news',
    label: '関西住宅・不動産',
    url: 'https://news.google.com/rss/search?q=%E9%96%A2%E8%A5%BF+%E4%BD%8F%E5%AE%85+%E4%B8%8D%E5%8B%95%E7%94%A3&hl=ja&gl=JP&ceid=JP:ja',
  },
  {
    category: 'companies',
    label: '対象企業ニュース',
    url: 'https://news.google.com/rss/search?q=%E9%A3%AF%E7%94%B0%E3%82%B0%E3%83%AB%E3%83%BC%E3%83%97+OR+%E3%82%B1%E3%82%A4%E3%82%A2%E3%82%A4%E3%82%B9%E3%82%BF%E3%83%BC+OR+%E4%BD%8F%E5%8F%8B%E6%9E%97%E6%A5%AD+OR+%E7%A9%8D%E6%B0%B4%E3%83%8F%E3%82%A6%E3%82%B9+OR+%E3%82%AA%E3%83%BC%E3%83%97%E3%83%B3%E3%83%8F%E3%82%A6%E3%82%B9&hl=ja&gl=JP&ceid=JP:ja',
  },
  {
    category: 'market_data',
    label: '住宅着工・価格統計',
    url: 'https://news.google.com/rss/search?q=%E6%96%B0%E8%A8%AD%E4%BD%8F%E5%AE%85%E7%9D%80%E5%B7%A5+OR+%E4%BD%8F%E5%AE%85%E4%BE%A1%E6%A0%BC+%E9%96%A2%E8%A5%BF&hl=ja&gl=JP&ceid=JP:ja',
  },
  {
    category: 'policy',
    label: '政策・規制動向',
    url: 'https://news.google.com/rss/search?q=%E4%BD%8F%E5%AE%85%E6%94%BF%E7%AD%96+%E5%A4%A7%E9%98%AA+OR+%E5%85%B5%E5%BA%AB+OR+%E4%BA%AC%E9%83%BD&hl=ja&gl=JP&ceid=JP:ja',
  },
];

function fetchRssFeeds() {
  const requests = RSS_FEEDS.map(feed => ({
    url: feed.url,
    method: 'GET',
    muteHttpExceptions: true,
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; GAS-KansaiHousingIntel/1.0)' },
  }));

  let responses;
  try {
    responses = UrlFetchApp.fetchAll(requests);
  } catch (e) {
    Logger.log('RSS fetchAll エラー: ' + e.message);
    return [];
  }

  const allItems = [];
  RSS_FEEDS.forEach((feed, i) => {
    try {
      const res = responses[i];
      if (res.getResponseCode() !== 200) {
        Logger.log('RSS エラー (' + feed.label + '): HTTP ' + res.getResponseCode());
        return;
      }
      const items = parseRssXml(res.getContentText(), feed.category, feed.label);
      allItems.push(...items);
    } catch (e) {
      Logger.log('RSS パースエラー (' + feed.label + '): ' + e.message);
    }
  });

  const recent = filterRecentItems(allItems, 48);
  Logger.log('RSS収集完了: ' + recent.length + '件');
  return recent;
}

function parseRssXml(xmlText, category, label) {
  const items = [];
  try {
    const doc = XmlService.parse(xmlText);
    const channel = doc.getRootElement().getChild('channel');
    if (!channel) return items;

    channel.getChildren('item').slice(0, 10).forEach(function(item) {
      try {
        items.push({
          category: category,
          label: label,
          title: cleanText(item.getChildText('title') || ''),
          link: item.getChildText('link') || '',
          pubDate: item.getChildText('pubDate') || '',
          description: cleanText(item.getChildText('description') || '').substring(0, 200),
          timestamp: parseRssDate(item.getChildText('pubDate') || ''),
        });
      } catch (e) {
        Logger.log('item パースエラー: ' + e.message);
      }
    });
  } catch (e) {
    Logger.log('XML パースエラー: ' + e.message);
  }
  return items;
}

function filterRecentItems(items, hoursBack) {
  const cutoff = new Date(Date.now() - hoursBack * 60 * 60 * 1000);
  return items
    .filter(function(item) { return !item.timestamp || item.timestamp >= cutoff; })
    .sort(function(a, b) { return (b.timestamp || 0) - (a.timestamp || 0); })
    .slice(0, 20);
}

function parseRssDate(dateStr) {
  if (!dateStr) return null;
  try { return new Date(dateStr); } catch (e) { return null; }
}

function cleanText(text) {
  if (!text) return '';
  return text
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function formatRssForReport(rssItems) {
  if (!rssItems || rssItems.length === 0) return '（RSSニュースなし）';

  const grouped = {};
  rssItems.forEach(function(item) {
    if (!grouped[item.label]) grouped[item.label] = [];
    grouped[item.label].push(item);
  });

  const lines = [];
  Object.keys(grouped).forEach(function(label) {
    lines.push('【' + label + '】');
    grouped[label].slice(0, 4).forEach(function(item) {
      const date = item.timestamp ? item.timestamp.toLocaleDateString('ja-JP') : '';
      lines.push('・' + item.title + (date ? ' (' + date + ')' : ''));
    });
  });
  return lines.join('\n');
}
