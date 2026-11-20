terraform {
  backend "s3" {
    bucket       = "terraform-backend-liesa-20261120"
    key          = "birdwatching/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}