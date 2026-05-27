use pyo3::prelude::*;

/// Constant-rate deadline calculator.
///
/// Uses integer nanosecond arithmetic to compute how many iterations
/// are due at a given point in time without cumulative float drift.
#[pyclass]
pub struct RateController {
    start_ns: u64,
    interval_ns: u64,
    tick: u64,
}

#[pymethods]
impl RateController {
    #[new]
    fn new(start_ns: u64, interval_ns: u64) -> Self {
        Self {
            start_ns,
            interval_ns: interval_ns.max(1),
            tick: 0,
        }
    }

    /// Advance to the current time and return ``(due_count, next_deadline_ns)``.
    fn advance(&mut self, now_ns: u64) -> (u64, u64) {
        let elapsed = now_ns.saturating_sub(self.start_ns);
        let target_tick = elapsed / self.interval_ns;
        let due = target_tick.saturating_sub(self.tick);
        self.tick = target_tick;
        let next = self.start_ns + (self.tick + 1) * self.interval_ns;
        (due, next)
    }

    /// Return the current tick count.
    fn tick(&self) -> u64 {
        self.tick
    }

    /// Return the configured interval in nanoseconds.
    fn interval_ns(&self) -> u64 {
        self.interval_ns
    }
}

/// Ramping arrival-rate deadline calculator.
///
/// Interpolates linearly between start and end rates across a stage
/// duration using ``f64`` arithmetic to avoid cumulative drift from
/// repeated Python float operations.
#[pyclass]
pub struct RampingRateController {
    stage_start_ns: u64,
    stage_duration_ns: f64,
    start_rate: f64,
    end_rate: f64,
    time_unit_ns: f64,
    tick: u64,
    accumulated_ns: f64,
}

#[pymethods]
impl RampingRateController {
    #[new]
    fn new(
        stage_start_ns: u64,
        stage_duration_ns: u64,
        start_rate: f64,
        end_rate: f64,
        time_unit_ns: f64,
    ) -> Self {
        Self {
            stage_start_ns,
            stage_duration_ns: stage_duration_ns as f64,
            start_rate: start_rate.max(0.1),
            end_rate: end_rate.max(0.1),
            time_unit_ns: time_unit_ns.max(1.0),
            tick: 0,
            accumulated_ns: 0.0,
        }
    }

    /// Advance to the current time and return ``(due_count, next_deadline_ns)``.
    fn advance(&mut self, now_ns: u64) -> (u64, u64) {
        let elapsed_ns = now_ns.saturating_sub(self.stage_start_ns) as f64;
        let mut due: u64 = 0;

        while self.accumulated_ns <= elapsed_ns {
            let progress = if self.stage_duration_ns > 0.0 {
                (self.accumulated_ns / self.stage_duration_ns).min(1.0)
            } else {
                1.0
            };
            let rate = self.start_rate + (self.end_rate - self.start_rate) * progress;
            let rate = rate.max(0.1);
            let interval = self.time_unit_ns / rate;
            self.accumulated_ns += interval;

            if self.accumulated_ns <= elapsed_ns {
                due += 1;
                self.tick += 1;
            }
        }

        let next = self.stage_start_ns + self.accumulated_ns as u64;
        (due, next)
    }

    /// Return the current tick count.
    fn tick(&self) -> u64 {
        self.tick
    }
}
