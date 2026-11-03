// проба (аудит M3310-R11-03): формат TypeScript сканер не разбирает — сам файл находка FORMAT
export default (db: any, x: string) => db.query("SELECT " + x);
