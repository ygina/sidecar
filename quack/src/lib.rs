pub mod arithmetic {
    mod modint;
    mod evaluator;

    pub use modint::ModularInteger;
    pub use modint::init_pow_table;
    pub use modint::MEMOIZED_POWER;
    pub use evaluator::MonicPolynomialEvaluator;
}

mod quack_internal;
pub use quack_internal::*;

pub type Identifier = u16;
pub type IdentifierLog = Vec<Identifier>;

pub trait Quack {
    fn new(threshold: usize) -> Self;
    fn insert(&mut self, value: Identifier);
    fn remove(&mut self, value: Identifier);
    fn threshold(&self) -> usize;
    fn count(&self) -> u16;
}
