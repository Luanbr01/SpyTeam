/* Conversões de unidades e decodificação local do percurso. Sem envio de GPS a outro serviço. */
((root) => {
    'use strict';
    function number(value) {
        if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
        const n = Number(value);
        return Number.isFinite(n) && n >= 0 ? n : null;
    }
    function group(sport) {
        if (['Run', 'TrailRun', 'VirtualRun'].includes(sport)) return 'run';
        if (sport === 'Swim') return 'swim';
        if (sport === 'WeightTraining') return 'strength';
        return 'other';
    }
    const names = {Run: 'Corrida', TrailRun: 'Corrida em trilha', VirtualRun: 'Corrida virtual',
        Swim: 'Natação', WeightTraining: 'Musculação', Workout: 'Treino', Ride: 'Ciclismo',
        VirtualRide: 'Ciclismo virtual', MountainBikeRide: 'Mountain bike', GravelRide: 'Ciclismo gravel',
        EBikeRide: 'Bicicleta elétrica', Walk: 'Caminhada', Hike: 'Trilha', Yoga: 'Yoga',
        Crossfit: 'CrossFit', HighIntensityIntervalTraining: 'HIIT', Elliptical: 'Elíptico'};
    function sportName(sport) { return names[sport] || sport || 'Atividade'; }
    function numeric(value, digits = 2) { return value.toLocaleString('pt-BR', {maximumFractionDigits: digits}); }
    function duration(value) {
        const n = number(value);
        if (n === null) return '—';
        const s = Math.round(n), hours = Math.floor(s / 3600), minutes = Math.floor(s / 60) % 60;
        return hours ? `${hours}h ${String(minutes).padStart(2, '0')}min ${String(s % 60).padStart(2, '0')}s` :
            `${minutes}min ${String(s % 60).padStart(2, '0')}s`;
    }
    function distance(item) {
        const meters = number(item.distance);
        if (meters === null) return '—';
        return group(item.sport_type) === 'swim' ? `${numeric(meters, 0)} m` : `${numeric(meters / 1000)} km`;
    }
    function rhythm(item) {
        const meters = number(item.distance), seconds = number(item.moving_time);
        const swim = group(item.sport_type) === 'swim';
        const pace = swim || group(item.sport_type) === 'run' || ['Walk', 'Hike'].includes(item.sport_type);
        if (pace) {
            const unit = swim ? 'min/100 m' : 'min/km';
            if (!meters || !seconds) return {label: 'Pace médio', value: '—', note: 'Pace indisponível: requer distância e tempo em movimento maiores que zero.'};
            const rounded = Math.round(seconds * (swim ? 100 : 1000) / meters);
            return {label: 'Pace médio', value: `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')} ${unit}`,
                note: 'Pace calculado pelo tempo em movimento dividido pela distância. Pode diferir do ritmo ajustado mostrado pelo Strava.'};
        }
        if (group(item.sport_type) === 'strength' || !meters) return {label: 'Pace médio', value: '—', note: 'Esta atividade não possui pace aplicável.'};
        const speed = number(item.average_speed) || (seconds ? meters / seconds : null);
        return {label: 'Velocidade média', value: speed ? `${numeric(speed * 3.6, 1)} km/h` : '—', note: 'Velocidade média da atividade; o tempo total inclui as pausas.'};
    }
    function date(item) {
        // O horário local da atividade não deve ser convertido novamente para o fuso do navegador.
        const local = String(item.start_date_local || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
        if (local) return `${local[3]}/${local[2]}/${local[1]} às ${local[4]}:${local[5]}`;
        const value = new Date(item.start_date || '');
        return Number.isNaN(value.getTime()) ? 'Data não informada' : value.toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
    }
    function decodePolyline(encoded) {
        if (typeof encoded !== 'string' || !encoded || encoded.length > 200000) return [];
        let index = 0, lat = 0, lng = 0;
        const points = [];
        function component() {
            let value = 0, shift = 0, byte;
            do {
                if (index >= encoded.length || shift > 30) throw new Error('Percurso inválido');
                byte = encoded.charCodeAt(index++) - 63;
                if (byte < 0 || byte > 63) throw new Error('Percurso inválido');
                value += (byte & 31) * Math.pow(2, shift);
                shift += 5;
            } while (byte >= 32);
            return value % 2 ? -(Math.floor(value / 2) + 1) : value / 2;
        }
        try {
            while (index < encoded.length) {
                lat += component(); lng += component();
                if (Math.abs(lat) > 9000000 || Math.abs(lng) > 18000000) return [];
                points.push([lat / 1e5, lng / 1e5]);
            }
            return points.length > 1 ? points : [];
        } catch (_) { return []; }
    }
    const api = {number, group, sportName, numeric, duration, distance, rhythm, date, decodePolyline};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.StravaView = api;
})(typeof window !== 'undefined' ? window : globalThis);
