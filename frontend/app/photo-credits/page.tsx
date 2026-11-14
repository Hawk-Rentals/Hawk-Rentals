import photos from "../vehiclePhotos.json";

export default function PhotoCredits() {
  return <main className="manage-page"><p className="eyebrow">BEHIND THE FLEET</p><h1>Vehicle photo credits.</h1><p className="muted">Photos illustrate each model. The year, colour, and trim of your rental may differ. Photos are resized and cropped to fit the cards.</p><div className="table-scroll"><table><thead><tr><th>Vehicle</th><th>Photographer / source</th><th>Licence</th></tr></thead><tbody>{photos.map((photo) => <tr key={photo.vehicle}><td>{photo.vehicle}</td><td><a className="text-link" href={photo.source} target="_blank" rel="noreferrer">{photo.author}</a></td><td><a className="text-link" href={photo.licenseUrl} target="_blank" rel="noreferrer">{photo.license}</a></td></tr>)}</tbody></table></div></main>;
}
